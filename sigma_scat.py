
import numpy as np
#np.seterr(all='warn')
import constants as c
import dust
import cmindex as cmi
import scatmodels as sms
from scipy.interpolate import interp1d
from scipy.integrate import trapz

# from multiprocessing import Pool
#from pathos.multiprocessing import Pool

#----------------------------------------------------------
# evals( emin=1.0, emax=2.0, de=0.1 ) : np.array [keV]
# angles( thmin=5.0, thmax=100.0, dth=5.0 ) : np.array [arcsec]
#

def evals( emin=1.0, emax=2.0, de=0.1 ):
    """ 
    FUNCTION evals( emin=1.0, emax=2.0, de=0.1 )
    RETURNS : np.array
    Distribution of energies [keV]
    """
    return np.arange( emin, emax+de, de )

def angles( thmin=5.0, thmax=100.0, dth=5.0 ):
    """
    FUNCTION angles( thmin=5.0, thmax=100.0, dth=5.0 )
    RETURNS : np.array
    Distribution of angles [arcsec]
    """
    return np.arange( thmin, thmax+dth, dth )

#-------------- Tie scattering mechanism to an index of refraction ------------------

class Scatmodel(object):
    """
    OBJECT Scatmodel( smodel=RGscat(), cmodel=cmi.CmDrude() )
    smodel : scattering model type object : RGscat(), Mie()
    cmodel : cmindex type object : CmDrude(), CmGraphite(), CmSilicate()
    stype  : string : 'RGscat', 'Mie'
    cmtype : 'Drude', 'Silicate', 'Graphite'
    """
    def __init__( self, smodel=sms.RGscat(), cmodel=cmi.CmDrude() ):
        self.smodel = smodel
        self.cmodel = cmodel
        self.stype  = smodel.stype
        self.cmtype = cmodel.cmtype
        # cmtype choices : 'Drude' (requires rho term only)
        #                  'Graphite' (Carbonaceous grains)
        #                  'Silicate' (Astrosilicate)
        #                  --- Graphite and Silicate values come from Draine (2003)

#-------------- Quickly make a common Scatmodel object ---------------------------

def makeScatmodel( model_name, material_name ):
    """
    FUNCTION makeScatmodel( model_name, material_name )
    RETURNS Scatmodel object
    ----------------------------------------------------
    model_name    : string : 'RG' or 'Mie'
    material_name : string : 'Drude', 'Silicate', 'Graphite', 'SmallGraphite'
    """

    if model_name == 'RG':
        sm = sms.RGscat()
    elif model_name == 'Mie':
        sm = sms.Mie()
    else:
        print 'Error: Model name not recognized'
        return

    if material_name == 'Drude':
        cm = cmi.CmDrude()
    elif material_name == 'Silicate':
        cm = cmi.CmSilicate()
    elif material_name == 'Graphite':
        cm = cmi.CmGraphite()
    elif material_name == 'SmallGraphite': # Small Graphite ~ 0.01 um
        cm = cmi.CmGraphite( size='small' )
    else:
        print 'Error: CM name not recognized'
        return

    return Scatmodel( sm, cm )


#-------------- Various Types of Scattering Cross-sections -----------------------

class Diffscat(object):
    """
    A differential scattering cross-section [cm^2 ster^-1]
    --------------------------------------------------------------
    OBJECT Diffscat( scatm=Scatmodel(), theta=angles() [arcsec], E=1.0 [keV], a=1.0 [um] )
    scatm : Scatmodel
    theta : np.array : arcsec
    E     : scalar or np.array : Note, must match number of theta values if size > 1
    a     : scalar : um
    dsig  : np.array : cm^2 ster^-1
    """
    def __init__( self, scatm=Scatmodel(), theta=angles(), E=1.0, a=1.0 ):
        self.scatm  = scatm
        self.theta  = theta
        self.E      = E
        self.a      = a

        cm   = scatm.cmodel
        scat = scatm.smodel

        if cm.cmtype == 'Graphite':
            dsig_pe = scat.Diff( theta=theta, a=a, E=E, cm=cmi.CmGraphite(size=cm.size, orient='perp') )
            dsig_pa = scat.Diff( theta=theta, a=a, E=E, cm=cmi.CmGraphite(size=cm.size, orient='para') )
            self.dsig = ( dsig_pa + 2.0 * dsig_pe ) / 3.0
        else:
            self.dsig   = scat.Diff( theta=theta, a=a, E=E, cm=cm )

class Sigmascat(object):
    """
    Total scattering cross-section [cm^2]
    ---------------------------------------------------------
    OBJECT Sigmascat( scatm=Scatmodel(), E=1.0 [keV], a=1.0 [um] )
    scatm : Scatmodel
    E     : scalar or np.array : keV
    a     : scalar : um
    qsca  : scalar or np.array : unitless scattering efficiency
    sigma : scalar or np.array : cm^2
    """
    def __init__( self, scatm=Scatmodel(), E=1.0, a=1.0 ):
        self.scatm  = scatm
        self.E      = E
        self.a      = a

        cm   = scatm.cmodel
        scat = scatm.smodel

        cgeo  = np.pi * np.power( a*c.micron2cm(), 2 )

        if cm.cmtype == 'Graphite':
            qsca_pe = scat.Qsca( a=a, E=E, cm=cmi.CmGraphite(size=cm.size, orient='perp') )
            qsca_pa = scat.Qsca( a=a, E=E, cm=cmi.CmGraphite(size=cm.size, orient='para') )
            self.qsca = ( qsca_pa + 2.0*qsca_pe ) / 3.0
        else:
            self.qsca = scat.Qsca( a=a, E=E, cm=cm )

        self.sigma = self.qsca * cgeo

class Sigmaext(object):
    """
    Total EXTINCTION cross-section [cm^2]
    ---------------------------------------------------------
    OBJECT Sigmascat( scatm=Scatmodel(), E=1.0 [keV], a=1.0 [um] )
    scatm : Scatmodel
    E     : scalar or np.array : keV
    a     : scalar : um
    qext  : scalar or np.array : unitless extinction efficiency
    sigma : scalar or np.array : cm^2
    """
    def __init__( self, scatm=Scatmodel(), E=1.0, a=1.0 ):
        self.scatm  = scatm
        self.E      = E
        self.a      = a

        if scatm.stype == 'RG':
            print 'Rayleigh-Gans cross-section not currently supported for Kappaext'
            self.sigma = None
            return

        cm   = scatm.cmodel
        scat = scatm.smodel

        cgeo  = np.pi * np.power( a*c.micron2cm(), 2 )

        if cm.cmtype == 'Graphite':
            qext_pe = scat.Qext( a=a, E=E, cm=cmi.CmGraphite(size=cm.size, orient='perp') )
            qext_pa = scat.Qext( a=a, E=E, cm=cmi.CmGraphite(size=cm.size, orient='para') )
            self.qext = ( qext_pa + 2.0*qext_pe ) / 3.0
        else:
            self.qext = scat.Qext( a=a, E=E, cm=cm )

        self.sigma = self.qext * cgeo

class Kappascat(object):
    """
    Opacity to scattering [g^-1 cm^2]
    OBJECT Kappascat( E=1.0 [keV], scatm=Scatmodel(), dist=dust.Dustspectrum() )
    ---------------------------------
    E     : scalar or np.array : keV, photon energy
    scatm : Scatmodel
    dist  : dust.Dustspectrum
    kappa : scalar or np.array : cm^2 g^-1, typically
    
    ---------------------------------
    To call this class:
    ---------------------------------
    kappa = Kappascat()
    kappa(E) computes integral of scattering cross-section over grain size distribution    
    """
    def __init__( self, E=1.0, scatm=Scatmodel(), dist=dust.Dustspectrum() ):
        self.E      = E
        self.kappa  = None
        self.scatm  = scatm
        self.dist   = dist

    def __call__(self, with_mp=False):
        cm   = self.scatm.cmodel
        scat = self.scatm.smodel

        # geometric cross-section
        cgeo = np.pi * np.power( self.dist.a * c.micron2cm(), 2 )
        
        if cm.cmtype == 'Graphite':
            qsca_pe = scat.Qsca( self.E, a=self.dist.a, cm=cmi.CmGraphite(size=cm.size, orient='perp') )
            qsca_pa = scat.Qsca( self.E, a=self.dist.a, cm=cmi.CmGraphite(size=cm.size, orient='para') )
            qsca    = ( qsca_pa + 2.0 * qsca_pe ) / 3.0
        else:
            qsca = scat.Qsca( self.E, self.dist.a, cm=cm )

        integrand  = self.dist.nd[None,:] * qsca * cgeo[None,:] / self.dist.md
        kappa      = trapz( integrand, self.dist.a, axis=1 )
        self.kappa = kappa


class Kappaext(object):
    """
    Opacity to EXTINCTION [g^-1 cm^2]
    OBJECT Kappaext( E=1.0 [keV], scatm=Scatmodel(), dist=dust.Dustspectrum() )
    ---------------------------------
    scatm : Scatmodel
    E     : scalar or np.array : keV
    dist  : dust.Dustspectrum
    kappa : scalar or np.array : cm^2 g^-1, typically
        
    ---------------------------------
    To call this class:
    ---------------------------------
    kappa = Kappaext()
    kappa(E) computes integral of extinction cross-section over grain size distribution
    """
    def __init__( self, E=1.0, scatm=Scatmodel(), dist=dust.Dustspectrum() ):
        self.scatm  = scatm
        self.E      = E
        self.dist   = dist

        if scatm.stype == 'RG':
            print 'Rayleigh-Gans cross-section not currently supported for Kappaext'
            self.kappa = None
            return

    def __call__(self):
        cm   = self.scatm.cmodel
        scat = self.scatm.smodel

        # geometric cross section
        cgeo = np.pi * np.power( self.dist.a * c.micron2cm(), 2 )
        
        if cm.cmtype == 'Graphite':
            qext_pe = scat.Qext( self.E, a=self.dist.a, cm=cmi.CmGraphite(size=cm.size, orient='perp') )
            qext_pa = scat.Qext( self.E, a=self.dist.a, cm=cmi.CmGraphite(size=cm.size, orient='para') )
            qext    = ( qext_pa + 2.0 * qext_pe ) / 3.0
        else:
            qext = scat.Qext( self.E, self.dist.a, cm=cm )

        integrand  = self.dist.nd[None,:] * qext * cgeo[None,:] / self.dist.md
        kappa      = trapz( integrand, self.dist.a, axis=1 )
        self.kappa = kappa


                                                        

#-------------- Objects that can be used for interpolation later -----------------

class KappaSpec( object ):
    """
    OBJECT Kappaspec( E=None, kappa=None, scatm=None, dspec=None )
    E     : np.array : keV
    scatm : Scatmodel
    dspec : dust.Dustspectrum
    kappa : scipy.interpolate.interp1d object with (E, kappa) as arguments
    """
    def __init__(self, E=None, kappa=None, scatm=None, dspec=None ):
        self.E = E
        self.kappa = interp1d( E, kappa )
        self.scatm = scatm
        self.dspec = dspec

class SigmaSpec( object ):
    """
    OBJECT Sigmaspec( E=None, sigma=None, scatm=None )
    E     : np.array : keV
    scatm : Scatmodel
    sigma : scipy.interpolate.interp1d object with (E, sigma) as arguments
    """
    def __init__(self, E=None, sigma=None, scatm=None):
        self.E = E
        self.sigma = interp1d( E, sigma )
        self.scatm = scatm
