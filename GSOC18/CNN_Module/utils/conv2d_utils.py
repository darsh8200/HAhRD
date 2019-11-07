import tensorflow as  tf

################ Tensorflow Constants ###########################
#To fix a graph level for all ops to be repetable across session
graph_level_seed=1
tf.set_random_seed(graph_level_seed)
############### Global Variables ################################
#the datatype of all the variables and the placeholder
dtype=tf.float32    #this could save memory

################ Weight Initialization ##########################
def get_variable_on_cpu(name,shape,initializer,weight_decay=None):
    '''
    DESCRIPTION:
        Since we wull be using a multi GPU, we will follow a model
        of having a shared weight among all worker GPU, which will be
        initialized in CPU.
        (See Tesnorflow website for more information about model)
        Inspiration of this function:
        https://github.com/tensorflow/models/blob/master/tutorials/image/cifar10/cifar10.py
    USAGE:
        INPUTS:
            name        :the name of weight variable (W/b)
            shape       :the shape of the variable
            weight_decay:(lambda)if not None then the value specified will be used for L2 regularization
            initializer :the name of the variable initializer
        OUTPUTS:
            weight      :the weight variable created
    '''
    #Initializing the variable on CPU for sharing weights among GPU
    with tf.device('/cpu:0'):
        weight=tf.get_variable(name,shape=shape,dtype=dtype,
                        initializer=initializer)
        #tf.summary.histogram(name,weight) #we will add them in training script

    if not weight_decay==None:
        #Applying the l2 regularization and multiplying with
        #the hyperparameter weight_decay: lambda
        reg_loss=tf.multiply(tf.nn.l2_loss(weight),weight_decay,
                                name='lambda_hyparam')
        #Adding the loss to the collection so that it could be added to final loss.
        tf.add_to_collection('all_losses',reg_loss)

    return weight

################ Simple Feed Forward Layers ###################
def simple_fully_connected(X,name,output_dim,is_training,dropout_rate=0.0,
                            apply_batchnorm=True,weight_decay=None,
                            flatten_first=False,apply_relu=True,
                            initializer=tf.glorot_uniform_initializer()):
    '''
    DESCRIPTION:
        This function will implement a simple feed-foreward network,
        taking the activation X of previous layer/input layer,
        transforming it linearly and then passing it through a
        desired non-linear activation.
    USAGE:
        INPUT:
            X           :the activation of previous layer/input layer
            output_dim  :the dimension of the output layer
            name        :the name of the layer
            weight_decay:(lambda) if specified to a value, then it
                            will be used for implementing the L2-
                            regularization of the weights
            is_training : to be used to state the mode i.e training or
                            inference mode.used for batchnorm
            dropout_rate: the fraction of the activation which we will
                            dropout randomly to act as a regularizing effect.
                            a number between 0 an 1.
            apply_batchnorm: whether to apply batchnorm or not. A boolean
                            True/False.
            weight_decay : an hyperparameter which will control the fraction
                            of L2- norm of weights to add in total loss.
                            Will act as regularization effect.
            flatten_first: whether to first flatten the input into a
                            2 dimensional tensor as [batch_size,all_activation]
            apply_relu  : whether to apply relu activation at last or not.
            initializer :initializer choice to be used for Weights

        OUTPUT:
            A           : the activation of this layer
    '''
    with tf.variable_scope(name):
        #Flattening the input if necessary
        if flatten_first==True:
            X=tf.contrib.layers.flatten(X)

        input_dim=X.get_shape().as_list()[1]
        #Checking the dimension of the input
        if not len(X.get_shape().as_list())==2:
            raise AssertionError('The X should be of shape: (batch,all_nodes)')

        #Get the hold of necessary variable
        shape_W=(input_dim,output_dim)
        shape_b=(1,output_dim)
        W=get_variable_on_cpu('W',shape_W,initializer,weight_decay)

        #Applying the linear transformation and passing through non-linearity
        Z=tf.matmul(X,W,name='linear_transform')

        #Applying batch norm
        if apply_batchnorm==True:
            with tf.variable_scope('batch_norm'):
                axis=1      #here the features are in axis 1
                Z_tilda=tf.layers.batch_normalization(Z,axis=axis,
                                                    training=is_training)
        else:
            #We generally don't regularize the bias unit
            bias_initializer=tf.zeros_initializer()
            b=get_variable_on_cpu('b',shape_b,bias_initializer)
            Z_tilda=tf.add(Z,b,name='bias_add')

        if apply_relu==True:
            with tf.variable_scope('rl_dp'):
                A=tf.nn.relu(Z_tilda,name='relu')
                #Adding dropout to the layer with drop_rate parameter
                A=tf.layers.dropout(A,rate=dropout_rate,training=is_training,
                                    name='dropout')
        else:
            A=Z_tilda

    return A

################ Convlutional Layers ##########################
def rectified_conv2d(X,name,filter_shape,output_channel,
                    stride,padding_type,is_training,dropout_rate=0.0,
                    apply_batchnorm=True,weight_decay=None,apply_relu=True,
                    initializer=tf.glorot_uniform_initializer()):
    '''
    DESCRIPTION:
        This function will apply simple convolution to the given input
        images filtering the input with required number of filters.
        This will be a custom block to apply the whole rectified
        convolutional block which include the following sequence of operation.
        conv2d --> batch_norm(optional) --> activation(optional)
    USAGE:
        INPUT:
            X              : the input 'image' to this layer. A 4D tensor of
                             shape [batch,input_height,input_width,input_channel]
            name           : the name of the this convolution layer. This will
                                be useful in grouping the components together.
                                (so currently kept as compulsory)
            filter_shape   : a tuple of form (filter_height,filter_width)
            output_channel : the total nuber of output channels in the
                             feature 'image/activation' of this layer
            stride         : a tuple giving (stride_height,stride_width)
            padding_type   : string either to do 'SAME' or 'VALID' padding
            is_training    : (used with batchnorm) a boolean to specify
                                whether we are in training or inference mode.
            dropout_rate   : the fraction of final activation to drop from the
                             last activation of this layer.
                            It will act as regularization effect.
            apply_batchnorm: a boolean to specify whether to use batch norm or
                                not.Defaulted to True since bnorm is useful
            weight_decay   : give a value of regularization hyperpaprameter
                                i.e the amount we want to have l2-regularization
                                on the weights. defalut no regularization.
            apply_relu     : this will be useful if we dont want to apply relu
                                but some other activation function diretly
                                during the model description. Then this function
                                will not do rectification.
            initializer    : the initializer for the filter Variables
        OUTPUT:
            A       :the output feature 'image' of this layer
    '''
    with tf.variable_scope(name):
        #Creating the filter weights and biases
        #Filter Weights
        input_channel=X.get_shape().as_list()[3]
        fh,fw=filter_shape
        net_filter_shape=(fh,fw,input_channel,output_channel)
        filters=get_variable_on_cpu('W',net_filter_shape,initializer,weight_decay)

        #stride and padding configuration
        sh,sw=stride
        net_stride=(1,sh,sw,1)
        if not (padding_type=='SAME' or padding_type=='VALID'):
            raise AssertionError('Please use SAME/VALID string for padding')

        #Now applying the convolution
        Z_conv=tf.nn.conv2d(X,filters,net_stride,padding_type,name='conv2d')
        if apply_batchnorm==True:
            Z=batch_normalization2d(Z_conv,is_training)
        else:
            #Biases Weight creation
            net_bias_shape=(1,1,1,output_channel)
            bias_initializer=tf.zeros_initializer()
            biases=get_variable_on_cpu('b',net_bias_shape,bias_initializer)
            Z=tf.add(Z_conv,biases,name='bias_add')

        #Finally applying the 'relu' activation
        if apply_relu==True:
            with tf.variable_scope('rl_dp'):
                A=tf.nn.relu(Z,name='relu')
                #Adding the dropout to the last layer
                A=tf.layers.dropout(A,rate=dropout_rate,training=is_training,
                                    name='dropout')
        else:
            A=Z #when we want to apply another activation outside in model.

    return A

def max_pooling2d(X,name,filter_shape,stride,padding_type):
    '''
    DESCRIPTION:
        This function will perform maxpooling on the input 'image'
        from the previous stage of convolutional layer.The parameters
        are similar to conv2d layer.
        But there are no trainable parameters in this layer.
    USAGE:
        INPUT:

        OUTPUT:
            A       : the maxpooled map of the input 'image' with same
                        number of channels
    '''
    with tf.variable_scope(name):
        #Writing the filter/kernel shape and stride in proper format
        fh,fw=filter_shape
        net_filter_shape=(1,fh,fw,1)
        sh,sw=stride
        net_stride=(1,sh,sw,1)

        #Applying maxpooling
        A=tf.nn.max_pool(X,net_filter_shape,net_stride,padding_type,name='max_pool')

    return A

def _batch_normalization2d(Z,is_training,name='batchnorm'):
    '''
    DESCRIPTION:
        (internal helper function to be used by simple conv2d)
        This function will add batch normalization on the feature map
        by normalizing the every feature map 'image' after transforming
        from the previous image to reduce the coupling between the
        two layers, thus making the current layer more roboust to the
        changes from the previous layers activation.
        (but useful with larger size,otherwise we have to seek alternative)
        like group norm etc.

        WARNING:
            we have to run a separate update operation to update the rolling
            averages of moments. This has to be taken care during final
            model declaration.Else inference will not work correctly.
    USAGE:
        INPUT:
            Z           : the linear activation (convolution) of conv2d layer
            is_training : a boolean to represent whether we are in training
                            mode or inference mode.(for rolling avgs of moments)
                            (a tf.bool type usually taken as placeholder)
        OUTPUT:
            Z_tilda     : the batch-normalized version of input
    '''
    with tf.variable_scope(name):
        axis=3  #We will normalize the whole feature map across batch
        Z_tilda=tf.layers.batch_normalization(Z,axis=axis,
                                            training=is_training)
    return Z_tilda

############### Residual Layers ##############################
def identity_residual_block(X,name,num_channels,mid_filter_shape,is_training,
                            dropout_rate=0.0,apply_batchnorm=True,weight_decay=None,
                            initializer=tf.glorot_uniform_initializer()):
    '''
    DESCRIPTION:
        This layer implements one of the special case of residual
        layer, when the shortcut/skip connection is directly connected
        to main branch without any extra projection since dimension
        (nH,nW) don't change in the main branch.
        We will be using bottle-neck approach to reduce computational
        complexity as mentioned in the ResNet Paper.

        There are three sub-layer in this layer:
        Conv1(one-one):F1 channels ---> Conv2(fh,fw):F2 channels
                        --->Conv3(one-one):F3 channels
    USAGE:
        INPUT:
            X               : the input 'image' to this layer
            name            : the name for this identity resnet block
            num_channels    :the number of channels/filters in each of sub-layer
                                a tuple of (F1,F2,F3)
            mid_filter_shape: (fh,fw) a tuple of shape of the filter to be used

        OUTPUT:
            A           : the output feature map/image of this layer
    '''
    with tf.variable_scope(name):
        #Applying the first one-one convolution
        A1=rectified_conv2d(X,name='branch_2a',
                            filter_shape=(1,1),
                            output_channel=num_channels[0],
                            stride=(1,1),
                            padding_type="VALID",
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            initializer=initializer)

        #Applying the Filtering in the mid sub-layer
        A2=rectified_conv2d(A1,name='branch_2b',
                            filter_shape=mid_filter_shape,
                            output_channel=num_channels[1],
                            stride=(1,1),
                            padding_type="SAME",
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            initializer=initializer)

        #Again one-one convolution for upsampling
        #Sanity check for the last number of channels which should match with input
        input_channels=X.get_shape().as_list()[3]
        if not input_channels==num_channels[2]:
            raise AssertionError('Identity Block: last sub-layer channels should match input')
        Z3=rectified_conv2d(A2,name='branch_2c',
                            filter_shape=(1,1),
                            output_channel=num_channels[2],
                            stride=(1,1),
                            padding_type="VALID",
                            is_training=is_training,
                            dropout_rate=0.0,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=False, #necessary cuz addition before activation
                            initializer=initializer)

        #Skip Connection
        #Adding the shortcut/skip connection
        with tf.variable_scope('skip_conn'):
            Z=tf.add(Z3,X)
            A=tf.nn.relu(Z,name='relu')

        #Adding dropout to the last sub-layer of this block
        A=tf.layers.dropout(A,rate=dropout_rate,training=is_training,name='dropout')
    return A

def convolutional_residual_block(X,name,num_channels,
                            first_filter_stride,mid_filter_shape,is_training,
                            dropout_rate=0.0,apply_batchnorm=True,weight_decay=None,
                            initializer=tf.glorot_uniform_initializer()):
    '''
    DESCRIPTION:
        This block is similar to the previous identity block but the
        only difference is that the shape (height,width) of main branch i.e 2
        is changed in the way, so we have to adjust this shape in the
        skip-connection/shortcut branch also. So we will use convolution
        in the shortcut branch to match the shape.
    USAGE:
        INPUT:
            first_filter_stride : (sh,sw) stride to be used with first filter

            Rest of the argument description is same as identity block
        OUTPUT:
            A   : the final output/feature map of this residual block
    '''
    with tf.variable_scope(name):
        #Main Branch
        #Applying the first one-one convolution
        A1=rectified_conv2d(X,name='branch_2a',
                            filter_shape=(1,1),
                            output_channel=num_channels[0],
                            stride=first_filter_stride,
                            padding_type="VALID",
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            initializer=initializer)

        #Applying the Filtering in the mid sub-layer
        A2=rectified_conv2d(A1,name='branch_2b',
                            filter_shape=mid_filter_shape,
                            output_channel=num_channels[1],
                            stride=(1,1),
                            padding_type="SAME",
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            initializer=initializer)

        #Again one-one convolution for upsampling
        #Here last number of channels which need not to match with input
        Z3=rectified_conv2d(A2,name='branch_2c',
                            filter_shape=(1,1),
                            output_channel=num_channels[2],
                            stride=(1,1),
                            padding_type="VALID",
                            is_training=is_training,
                            dropout_rate=0.0,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=False, #necessary cuz addition before activation
                            initializer=initializer)

        #Skip-Connection/Shortcut Branch
        #Now we have to bring the shortcut/skip-connection in shape and number of channels
        Z_shortcut=rectified_conv2d(X,name='branch_1',
                            filter_shape=(1,1),
                            output_channel=num_channels[2],
                            stride=first_filter_stride,
                            padding_type="VALID",
                            is_training=is_training,
                            dropout_rate=0.0,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=False, #necessary cuz addition before activation
                            initializer=initializer)

        #Finally merging the two branch
        with tf.variable_scope('skip_conn'):
            #now adding the two branches element wise
            Z=tf.add(Z3,Z_shortcut)
            A=tf.nn.relu(Z,name='relu')

        #Adding the dropout to the last sub-layer after skip-connection
        A=tf.layers.dropout(A,rate=dropout_rate,training=is_training,name='dropout')

    return A

############## Inception Module #############################
def inception_block(X,name,final_channel_list,compress_channel_list,
                    is_training,dropout_rate=0.0,
                    apply_batchnorm=True,weight_decay=None,
                    initializer=tf.glorot_uniform_initializer()):
    '''
    DESCRIPTION:
        This block will enable us to have multiple filter's activation
        in the same layer. Multiple filters (here only 1x1,3x3,5x5 and
        a maxpooling layer) will be applied to the input image and the
        output of all these filters will be stacked in one layer.

        This is biologically inspired where we first extract the feature
        of multiple frequency/filter and then combine it to further abstract
        the idea/image.

        Filters larger than 5 are not included as they will/could increase
        the computational complexity.
    USAGE:
        INPUT:
            X                   :the input image/tensor.
            name                :the name to be given to this whole block will be used in
                                    visualization
            final_channel_list : the list of channels as output of these filter
                                    [# 1x1 channels,# 3x3 channels,
                                    # 5x5 channels,# compressed maxpool channels]
            compress_channel_list: since we need to compress the input to do
                                    3x3 and 5x5 convolution. So we need the number
                                    of channels to compress into.
                                    list [#compressed channel for 3x3,
                                          #compressed channel for 5x5]
    '''
    with tf.variable_scope(name):
        #Starting with the direct one-one convolution to output
        A1=rectified_conv2d(X,
                            name='1x1',
                            filter_shape=(1,1),
                            output_channel=final_channel_list[0],
                            stride=(1,1),
                            padding_type='VALID',
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=True,
                            initializer=initializer)

        #Now starting the 3x3 convolution part
        #first compressing by 1x1
        C3=rectified_conv2d(X,
                            name='compress_3x3',
                            filter_shape=(1,1),
                            output_channel=compress_channel_list[0],
                            stride=(1,1),
                            padding_type='VALID',
                            is_training=is_training,
                            dropout_rate=0.0,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=True,
                            initializer=initializer)
        #now doing 3x3 convolution on this compressed 'image'
        A3=rectified_conv2d(C3,
                            name='3x3',
                            filter_shape=(3,3),
                            output_channel=final_channel_list[1],
                            stride=(1,1),
                            padding_type='SAME',
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=True,
                            initializer=initializer)

        #Now starting the same structure for the 5x5 conv part
        #first compressing by 1x1
        C5=rectified_conv2d(X,
                            name='compress_5x5',
                            filter_shape=(1,1),
                            output_channel=compress_channel_list[1],
                            stride=(1,1),
                            padding_type='VALID',
                            is_training=is_training,
                            dropout_rate=0.0,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=True,
                            initializer=initializer)
        #now doing 5x5 convolution on this compressed 'image'
        A5=rectified_conv2d(C5,
                            name='5x5',
                            filter_shape=(5,5),
                            output_channel=final_channel_list[2],
                            stride=(1,1),
                            padding_type='SAME',
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=True,
                            initializer=initializer)

        #Now adding the 3x3 maxpooling layer
        #first maxpooling
        CMp=max_pooling2d(X,
                          name='maxpool',
                          filter_shape=(3,3),
                          stride=(1,1),
                          padding_type='SAME')
        #now compressing to reduce channels
        AMp=rectified_conv2d(CMp,
                            name='compress_maxpool',
                            filter_shape=(1,1),
                            output_channel=final_channel_list[3],
                            stride=(1,1),
                            padding_type='VALID',
                            is_training=is_training,
                            dropout_rate=dropout_rate,
                            apply_batchnorm=apply_batchnorm,
                            weight_decay=weight_decay,
                            apply_relu=True,
                            initializer=initializer)

        #Now Concatenating the sub-channels of different filter types
        concat_list=[A1,A3,A5,AMp]
        axis=-1         #across the channel axis : axis=3
        A=tf.concat(concat_list,axis=axis,name='concat')

    return A
