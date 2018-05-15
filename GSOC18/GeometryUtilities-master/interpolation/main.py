#Helper function from this script
from hexCells_to_squareCell_interpolation import linear_interpolate_hex_to_square

#General Imports
import sys
import datetime
import cPickle as pickle
import matplotlib.pyplot as plt

#Shapely and Geometry File imports
from shapely.geometry import LineString,Polygon
from descartes.patch import PolygonPatch
from geometry.cmssw import read_geometry
input_default_file = '/data_CMS/cms/grasseau/HAhRD/test_triggergeom.root'

def plot_sq_cells(cell_d):
    t0=datetime.datetime.now()
    fig=plt.figure()
    ax1=fig.add_subplot(111)
    for id,cell in sq_cells_dict.items():
        poly=cell.polygon
        patch=PolygonPatch(poly,alpha=0.5,zorder=2,edgecolor='blue')
        ax1.add_patch(patch)
    t1=datetime.datetime.now()
    print '>>> Plot Completed in: ',t1-t0,' sec'
    ax1.set_xlim(-160, 160)
    ax1.set_ylim(-160, 160)
    ax1.set_aspect(1)
    plt.show()

def plot_hex_to_square_map(coef,hex_cells_dict,sq_cells_dict):
    t0=datetime.datetime.now()
    # fig=plt.figure()
    # ax1=fig.add_subplot(111)
    print '>>> Calculating the area of smallar cell for filtering'
    filter_hex_cells=([c.vertices.area for c in hex_cells_dict.values()
                        if len(list(c.vertices.exterior.coords))==7])
    small_wafer_area=min(filter_hex_cells)
    t1=datetime.datetime.now()
    print '>>> Area calculated %s in time: %s sec'%(
                                    small_wafer_area,t1-t0)
    t0=t1

    for hex_id,sq_overlaps in coef.items():
        hex_cell=hex_cells_dict[hex_id]
        poly=hex_cell.vertices
        #Filtering the cells in smaller region
        if poly.area!=small_wafer_area:
            continue

        fig=plt.figure()
        ax1=fig.add_subplot(111)
        x,y=poly.exterior.xy
        ax1.plot(x,y,'o',zorder=1)
        patch=PolygonPatch(poly,alpha=0.5,zorder=2,edgecolor='blue')
        ax1.add_patch(patch)
        print '>>> Plotting hex cell: ',hex_id
        for sq_cell_data in sq_overlaps:
            sq_cell_id=sq_cell_data[0]
            overlap_coef=sq_cell_data[1]
            sq_cell=sq_cells_dict[sq_cell_id]
            print ('overlapping with sq_cell: ',sq_cell_id,
                                    'with overlap coef: ',overlap_coef)
            poly=sq_cell.polygon
            x,y=poly.exterior.xy
            ax1.plot(x,y,'o',zorder=1)
            patch=PolygonPatch(poly,alpha=0.5,zorder=2,edgecolor='red')
            ax1.add_patch(patch)
        t1=datetime.datetime.now()
        print 'one hex cell overlap complete in: ',t1-t0,' sec\n'
        t0=t1
        #ax1.set_xlim(-160, 160)
        #ax1.set_ylim(-160, 160)
        #ax1.set_aspect(1)
        plt.show()

def generate_interpolation(hex_cell_dict_root):
    base_path=''
    ## Generating the overlapping coefficient
    hex_cells_dict=hex_cell_dict_root
    resolution=(500,500)
    layer=1
    sq_coef=linear_interpolate_hex_to_square(hex_cells_dict,
                                                layer,resolution)
    #Saving the generated coefficient as pickle file
    coef_filename=base_path+'sq_cells_data/coef_dict_layer_%s_res_%s.pkl'%(layer,
                                                            resolution[0])
    fhandle=open(coef_filename,'wb')
    pickle.dump(sq_coef,fhandle,protocol=pickle.HIGHEST_PROTOCOL)
    fhandle.close()
    #Reading the pickle file of saved coefficient
    print '>>> Reading the Overlap Coefficient File'
    fhandle=open(coef_filename,'rb')
    sq_coef=pickle.load(fhandle)
    fhandle.close()


    ## Plotting the sq cell for verification
    print '>>> Reading the Square Cells File'
    sq_filename=base_path+'sq_cells_data/sq_cells_dict_layer_%s_res_%s.pkl'%(layer,
                                                            resolution[0])
    fhandle=open(sq_filename,'rb')
    sq_cells_dict=pickle.load(fhandle)
    fhandle.close()

    #plot_sq_cells(sq_cells_dict)
    plot_hex_to_square_map(sq_coef,hex_cells_dict,sq_cells_dict)

def readGeometry( input_file,  layer, subdet ):
    t0 = datetime.datetime.now()
    treename = 'hgcaltriggergeomtester/TreeCells'
    cells = read_geometry(filename=input_file, treename=treename,
              subdet=subdet, layer=layer, wafer=-1)
    cells_d = dict([(c.id, c) for c in cells])
    t1 = datetime.datetime.now()
    print 'Cells read: number=', len(cells), ', time=', t1-t0
    return cells_d

if __name__=='__main__':
    import sys
    import optparse
    usage = 'usage: %prog [options]'
    parser = optparse.OptionParser(usage)
    parser.add_option('--input_geometry', dest='input_file', help='Input geometry file', default=input_default_file)
    # Not used
    # parser.add_option('--output', dest='output_file', help='Output pickle file', default='mapping.pkl')
    parser.add_option('--layer', dest='layer', help='Layer to be mapped', type='int', default=1)
    parser.add_option('--subdet', dest='subdet', help='Subdet', type='int', default=3)
    (opt, args) = parser.parse_args()
    if not opt.input_file:
      parser.print_help()
      print 'Error: Missing input geometry file name'
      sys.exit(1)
    cells_d = readGeometry( opt.input_file, opt.layer, opt.subdet )
    generate_interpolation(cells_d)
